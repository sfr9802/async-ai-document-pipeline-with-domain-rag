from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "ai" / "scripts"


def load_script(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"{name}_for_tests", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def test_context_enrichment_recovers_native_block_nearby_text_and_table_values(tmp_path: Path) -> None:
    module = load_script("rag_pdf_evidence_context_v2_enrichment")
    paths = write_context_fixture(tmp_path)

    report = module.run_enrichment(
        repair_report=paths["repair_report"],
        metadata_enrichment_report=paths["metadata_report"],
        local_storage_root=paths["local_storage"],
        output_report=tmp_path / "context.json",
        output_md=tmp_path / "context.md",
    )

    assert report["status"] == "PDF_EVIDENCE_CONTEXT_V2_READY_FOR_MANUAL_QUERY_AUTHORING"
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False
    assert report["summary"]["native_block_text_resolved_rows"] == 8
    assert report["summary"]["nearby_block_text_resolved_rows"] == 8
    assert report["summary"]["deterministic_table_ready_rows"] == 2
    assert report["summary"]["chart_or_table_label_without_body_rows"] == 1

    rows = {row["query_id"]: row for row in report["context_rows"]}
    paragraph = rows["gq_para"]
    assert paragraph["matched_block"]["block_id"] == "p4_b2"
    assert paragraph["text_context"]["native_block_text"] == "광공업 생산, 서비스업 생산, 건설투자는 감소"
    assert paragraph["text_context"]["text_bridge_status"] == "exact"
    assert [block["text"] for block in paragraph["nearby_blocks"][:2]] == [
        "2월중 전산업 생산은 전월대비 감소했다.",
        "소매판매는 증가했다.",
    ]

    export_table = rows["gq_export_table"]["table_context"]
    assert export_table["table_status"] == "deterministic_table_body"
    assert export_table["structured_table_claim_allowed"] is True
    assert export_table["headers"] == [
        "period",
        "수출(FOB) 금액",
        "수출(FOB) 증가율",
        "수입(CIF) 금액",
        "수입(CIF) 증가율",
        "수출입차 금액",
    ]
    assert export_table["row_values"][0] == {
        "period": "2025. 1",
        "수출(FOB) 금액": "491.9",
        "수출(FOB) 증가율": "△10.1",
        "수입(CIF) 금액": "510.6",
        "수입(CIF) 증가율": "△6.3",
        "수출입차 금액": "△18.7",
    }

    currency_table = rows["gq_currency_table"]["table_context"]
    assert currency_table["table_status"] == "deterministic_table_body"
    assert currency_table["row_values"][0]["period"] == "2018"
    assert currency_table["row_values"][0]["한국(원/달러) 기말"] == "1,118.1"
    assert currency_table["row_values"][0]["유로(달러/EUR) 절상률"] == "△4.18"

    chart_label = rows["gq_chart_label"]["table_context"]
    assert chart_label["table_status"] == "chart_or_table_label_without_body"
    assert chart_label["structured_table_claim_allowed"] is False
    assert chart_label["row_values"] == []

    title = rows["gq_title"]
    assert title["chunk_type"] == "title"
    assert title["answerability_gate"] == "NOT_ANSWERABLE_TITLE_OR_HEADING"
    assert title["candidate_for_answer_generation"] is False

    same_page = rows["gq_same_page_heading_near_table"]
    assert same_page["matched_block"]["block_id"] == "p60_b1"
    assert same_page["chunk_type"] != "table_body"
    assert same_page["table_context"]["structured_table_claim_allowed"] is False

    native_near_ocr = rows["gq_native_near_ocr"]
    assert native_near_ocr["answerability_gate"] == "EVIDENCE_TEXT_READY"
    assert [block["block_id"] for block in native_near_ocr["nearby_blocks"]] == ["p2_b2"]
    assert all(not block["ocr_used"] for block in native_near_ocr["nearby_blocks"])

    mismatch = rows["gq_mismatch"]
    assert mismatch["answerability_gate"] == "NEEDS_NATIVE_TEXT_REPAIR"
    assert "PDF_MATCHED_TEXT_NATIVE_BLOCK_MISMATCH" in mismatch["answerability_blockers"]
    assert mismatch["candidate_for_answer_generation"] is False


def test_context_enrichment_keeps_ocr_fragments_lower_trust_and_source_bound(tmp_path: Path) -> None:
    module = load_script("rag_pdf_evidence_context_v2_enrichment")
    paths = write_context_fixture(tmp_path)

    report = module.run_enrichment(
        repair_report=paths["repair_report"],
        metadata_enrichment_report=paths["metadata_report"],
        local_storage_root=paths["local_storage"],
        output_report=tmp_path / "context.json",
        output_md=tmp_path / "context.md",
    )

    row = next(row for row in report["context_rows"] if row["query_id"] == "gq_ocr")
    assert row["matched_block"]["block_id"] == "p0_ocr_0"
    assert row["chunk_type"] == "OCR_fragment"
    assert row["text_context"]["text_source"] == "ocr"
    assert row["ocr_context"]["ocr_used"] is True
    assert row["ocr_context"]["ocr_trust_label"] == "LOW_TRUST_OCR_FRAGMENT"
    assert row["answerability_gate"] == "OCR_REASSEMBLY_REQUIRED"
    assert row["candidate_for_answer_generation"] is False
    assert row["official_metric_input"] is False
    assert row["promotion_evidence"] is False


def test_context_enrichment_fails_closed_on_local_storage_escape(tmp_path: Path) -> None:
    module = load_script("rag_pdf_evidence_context_v2_enrichment")
    paths = write_context_fixture(tmp_path)
    payload = json.loads(paths["metadata_report"].read_text(encoding="utf-8"))
    payload["enriched_rows"][0]["source_metadata"]["parsed_artifact"]["storage_uri"] = "local://../escape.json"
    write_json(paths["metadata_report"], payload)

    report = module.run_enrichment(
        repair_report=paths["repair_report"],
        metadata_enrichment_report=paths["metadata_report"],
        local_storage_root=paths["local_storage"],
        output_report=tmp_path / "context.json",
        output_md=tmp_path / "context.md",
    )

    assert report["status"] == "FAILED_GUARDRAIL"
    assert report["validation"]["ok"] is False
    assert any("LOCAL_STORAGE_URI_ESCAPE" in error for error in report["validation"]["errors"])
    assert report["official_metric_input_rows"] == 0
    assert report["promotion_evidence"] is False


def test_canary_consumes_context_enrichment_so_native_and_table_evidence_survives(tmp_path: Path) -> None:
    enrichment_module = load_script("rag_pdf_evidence_context_v2_enrichment")
    canary_module = load_script("rag_pdf_evidence_object_v2_canary")
    paths = write_context_fixture(tmp_path)
    context_report = enrichment_module.run_enrichment(
        repair_report=paths["repair_report"],
        metadata_enrichment_report=paths["metadata_report"],
        local_storage_root=paths["local_storage"],
        output_report=tmp_path / "context.json",
        output_md=tmp_path / "context.md",
    )
    write_json(tmp_path / "context.json", context_report)
    write_json(
        tmp_path / "lineage.json",
        {
            "status": "PDF_GOLD_EVIDENCE_LINEAGE_AUDIT_COMPLETE",
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "official_denominator_registry_opened": False,
            "validation": {"ok": True, "errors": []},
            "lineage_rows": [],
            "prior_good_candidate_rows": [],
        },
    )

    report = canary_module.run_canary(
        repair_report=paths["repair_report"],
        lineage_report=tmp_path / "lineage.json",
        context_enrichment_report=tmp_path / "context.json",
        output_report=tmp_path / "canary.json",
        output_md=tmp_path / "canary.md",
        include_prior_review_rows=False,
    )

    assert report["status"] == "PDF_EVIDENCE_OBJECT_V2_CANARY_COMPLETE"
    assert report["summary"]["native_block_text_missing_rows"] == 0
    assert report["summary"]["locator_only_context_rows"] == 0
    rows = {row["query_id"]: row for row in report["canary_rows"]}
    assert rows["gq_export_table"]["answerability_gate"] == "TABLE_PARSER_READY"
    assert rows["gq_export_table"]["table_values"][0]["period"] == "2025. 1"
    assert "수출(FOB) 금액=491.9" in rows["gq_export_table"]["answerable_evidence_text"]
    assert rows["gq_title"]["answerability_gate"] == "NOT_ANSWERABLE_TITLE_OR_HEADING"
    assert rows["gq_title"]["candidate_for_local_llm"] is False


def write_context_fixture(tmp_path: Path) -> dict[str, Path]:
    local_storage = tmp_path / "local-storage"
    parsed_path = local_storage / "doc-a" / "pdf_parsed_json" / "parsed.json"
    write_json(parsed_path, parsed_fixture())
    rows = repair_rows()
    metadata_rows = []
    for row in rows:
        enriched = dict(row)
        enriched["source_metadata"] = {
            "parsed_artifact": {
                "id": "pa-doc-a",
                "storage_uri": "local://doc-a/pdf_parsed_json/parsed.json",
            },
            "parser": {"parser_name": "pymupdf", "parser_version": "pdf-extract-v1"},
            "location_json": {
                "page_no": row["page"],
                "physical_page_index": row["physical_page_index"],
                "bbox": row["bbox"],
                "block_type": row["region_type"],
            },
            "page_metadata": {
                "ocr_used": row.get("OCR_fallback_used") is True,
                "ocr_confidence_avg": row.get("OCR_confidence"),
                "table_count": 0,
            },
        }
        metadata_rows.append(enriched)

    repair_report = tmp_path / "repair.json"
    metadata_report = tmp_path / "metadata.json"
    write_json(
        repair_report,
        {
            "status": "PDF_EVIDENCE_READINESS_REPAIR_COMPLETE",
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "repair_rows": rows,
        },
    )
    write_json(
        metadata_report,
        {
            "status": "PDF_EVIDENCE_METADATA_ENRICHMENT_COMPLETE",
            "official_metric_input_rows": 0,
            "promotion_evidence": False,
            "enriched_rows": metadata_rows,
        },
    )
    return {"local_storage": local_storage, "repair_report": repair_report, "metadata_report": metadata_report}


def repair_rows() -> list[dict]:
    return [
        {
            "query_id": "gq_title",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-title",
            "page": 2,
            "physical_page_index": 1,
            "bbox": [116.28, 238.77, 439.32, 276.81],
            "region_type": "paragraph",
            "matched_text": "최 근 경 제 동 향",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_para",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-para",
            "page": 5,
            "physical_page_index": 4,
            "bbox": [82.35, 150.44, 313.91, 162.17],
            "region_type": "paragraph",
            "matched_text": "광공업 생산, 서비스업 생산, 건설투자는 감소",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_mismatch",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-mismatch",
            "page": 5,
            "physical_page_index": 4,
            "bbox": [82.35, 150.44, 313.91, 162.17],
            "region_type": "paragraph",
            "matched_text": "완전히 다른 문장",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_native_near_ocr",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-native-near-ocr",
            "page": 3,
            "physical_page_index": 2,
            "bbox": [70.0, 90.0, 220.0, 105.0],
            "region_type": "paragraph",
            "matched_text": "정상 native 문단",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_same_page_heading_near_table",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-same-page-heading",
            "page": 61,
            "physical_page_index": 60,
            "bbox": [70.0, 80.0, 180.0, 94.0],
            "region_type": "paragraph",
            "matched_text": "수출입 동향",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_export_table",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-export-table",
            "page": 61,
            "physical_page_index": 60,
            "bbox": [76.68, 103.92, 483.52, 672.6],
            "region_type": "paragraph",
            "matched_text": "수 출(FOB)\n수 입(CIF)\n수출입차",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_chart_label",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-chart",
            "page": 29,
            "physical_page_index": 28,
            "bbox": [240.83, 77.66, 313.57, 89.03],
            "region_type": "paragraph",
            "matched_text": "경상수지 추이",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_currency_table",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-currency",
            "page": 65,
            "physical_page_index": 64,
            "bbox": [73.6, 76.45, 239.27, 88.44],
            "region_type": "paragraph",
            "matched_text": "주요국가의 환율변동 비교",
            "native_text_available": True,
            "OCR_fallback_used": False,
            "content_evidence_lane": "pdf_content_evidence",
        },
        {
            "query_id": "gq_ocr",
            "source_file_id": "sf-a",
            "document_version_id": "doc-a",
            "search_unit_id": "su-ocr",
            "page": 1,
            "physical_page_index": 0,
            "bbox": [100.0, 100.0, 140.0, 115.0],
            "region_type": "ocr_line_group",
            "matched_text": "$32 }$",
            "native_text_available": False,
            "OCR_fallback_used": True,
            "OCR_confidence": 0.42,
            "content_evidence_lane": "pdf_content_evidence",
        },
    ]


def parsed_fixture() -> dict:
    return {
        "document_version_id": "doc-a",
        "parser_name": "pymupdf",
        "parser_version": "pdf-extract-v1",
        "filename": "fixture.pdf",
        "pages": [
            page(0, 1, True, True, [
                block("p0_ocr_0", "ocr_line_group", "$32 }$", [100.0, 100.0, 140.0, 115.0], 0, ocr=True, confidence=0.42),
                block("p0_ocr_1", "ocr_line_group", "2021. 3", [110.0, 130.0, 155.0, 145.0], 1, ocr=True, confidence=0.88),
            ], ocr_confidence_avg=0.65),
            page(1, 2, True, False, [
                block("p1_b0", "paragraph", "최 근 경 제 동 향", [116.28, 238.77, 439.32, 276.81], 0),
                block("p1_b1", "paragraph", "2025. 12.", [240.0, 290.0, 310.0, 305.0], 1),
            ]),
            page(2, 3, True, True, [
                block("p2_b0", "paragraph", "정상 native 문단", [70.0, 90.0, 220.0, 105.0], 0),
                block("p2_ocr_1", "ocr_line_group", "OCR 조각", [70.0, 110.0, 130.0, 124.0], 1, ocr=True, confidence=0.41),
                block("p2_b2", "paragraph", "다음 native 문단", [70.0, 130.0, 220.0, 145.0], 2),
            ], ocr_confidence_avg=0.41),
            page(4, 5, True, False, [
                block("p4_b1", "paragraph", "2월중 전산업 생산은 전월대비 감소했다.", [82.0, 130.0, 330.0, 145.0], 1),
                block("p4_b2", "paragraph", "광공업 생산, 서비스업 생산, 건설투자는 감소", [82.35, 150.44, 313.91, 162.17], 2),
                block("p4_b3", "paragraph", "소매판매는 증가했다.", [82.0, 170.0, 200.0, 182.0], 3),
                block("p4_b4", "paragraph", "설비투자도 증가했다.", [82.0, 190.0, 210.0, 202.0], 4),
            ]),
            page(28, 29, True, False, [
                block("p28_b0", "paragraph", "경상수지 추이", [240.83, 77.66, 313.57, 89.03], 0),
                block("p28_b1", "paragraph", "2월 경상수지는 80.3억 달러 흑자를 기록했다.", [80.0, 100.0, 400.0, 116.0], 1),
                block("p28_b2", "paragraph", "상품수지\n서비스수지\n경상수지\n(십억$)", [90.0, 130.0, 170.0, 200.0], 2),
                block("p28_b3", "paragraph", "2024.9\n10\n11\n12\n2025.1\n2", [180.0, 280.0, 360.0, 300.0], 3),
            ]),
            page(60, 61, True, False, [
                block("p60_b1", "paragraph", "수출입 동향", [70.0, 80.0, 180.0, 94.0], 1),
                block(
                    "p60_b2",
                    "paragraph",
                    "수 출(FOB)\n수 입(CIF)\n수출입차\n금 액\n증가율\n금 액\n증가율\n금 액\n"
                    "2025. 1\n491.9\n△10.1\n510.6\n△6.3\n△18.7\n"
                    "2025. 2\n522.9\n1.0\n488.0\n0.2\n34.9",
                    [76.68, 103.92, 483.52, 672.6],
                    2,
                ),
            ]),
            page(64, 65, True, False, [
                block("p64_b0", "paragraph", "주요국가의 환율변동 비교", [73.6, 76.45, 239.27, 88.44], 0),
                block("p64_b1", "paragraph", "한국(원/달러)\n일본(엔/달러)\n대만(NT달러/달러)\n유로(달러/EUR)", [80.0, 100.0, 450.0, 120.0], 1),
                block("p64_b2", "paragraph", "기말\n절상률\n기간평균\n기말\n절상률\n기말\n절상률\n기말\n절상률", [80.0, 125.0, 455.0, 145.0], 2),
                block(
                    "p64_b3",
                    "paragraph",
                    "2018\n1,118.1\n△4.18\n1,100.30\n110.36\n2.29\n30.57\n△2.45\n1.1441\n△4.18",
                    [80.0, 150.0, 455.0, 175.0],
                    3,
                ),
            ]),
        ],
    }


def page(
    physical_page_index: int,
    page_no: int,
    text_layer_present: bool,
    ocr_used: bool,
    blocks: list[dict],
    *,
    ocr_confidence_avg: float | None = None,
) -> dict:
    payload = {
        "physical_page_index": physical_page_index,
        "page_no": page_no,
        "page_label": str(page_no),
        "width": 595.0,
        "height": 842.0,
        "text_layer_present": text_layer_present,
        "ocr_used": ocr_used,
        "char_count": sum(len(block["text"]) for block in blocks),
        "blocks": blocks,
        "tables": [],
    }
    if ocr_confidence_avg is not None:
        payload["ocr_confidence_avg"] = ocr_confidence_avg
    return payload


def block(
    block_id: str,
    block_type: str,
    text: str,
    bbox: list[float],
    reading_order: int,
    *,
    ocr: bool = False,
    confidence: float | None = None,
) -> dict:
    payload = {
        "block_id": block_id,
        "block_type": block_type,
        "text": text,
        "bbox": bbox,
        "reading_order": reading_order,
        "section_path": [],
    }
    if ocr:
        payload.update(
            {
                "ocr_used": True,
                "ocr_engine": "paddleocr",
                "ocr_model": "PaddleOCR",
                "ocr_language": "korean",
                "ocr_confidence": confidence,
            }
        )
    return payload
