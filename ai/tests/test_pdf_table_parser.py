from __future__ import annotations

from app.capabilities.pdf.table_parser import extract_pdf_table_records


def test_pdf_table_parser_extracts_export_import_rows_from_single_native_block() -> None:
    records = extract_pdf_table_records(
        [
            block(
                "p60_b2",
                "수 출(FOB)\n수 입(CIF)\n수출입차\n금 액\n증가율\n금 액\n증가율\n금 액\n"
                "2025. 1\n491.9\n△10.1\n510.6\n△6.3\n△18.7",
                [76.68, 103.92, 483.52, 672.6],
                2,
            )
        ],
        page_no=61,
        physical_page_index=60,
    )

    assert len(records) == 1
    table = records[0]
    assert table["table_type"] == "export_import"
    assert table["headers"] == [
        "period",
        "수출(FOB) 금액",
        "수출(FOB) 증가율",
        "수입(CIF) 금액",
        "수입(CIF) 증가율",
        "수출입차 금액",
    ]
    assert table["source_block_ids"] == ["p60_b2"]
    assert table["bbox_granularity"] == "table_only"
    row = table["row_records"][0]
    assert row["row_label_normalized"] == "2025. 1"
    assert row["row_bbox"] == [76.68, 103.92, 483.52, 672.6]
    assert row["cells"][0] == {
        "column_path": "수출(FOB) 금액",
        "value_raw": "491.9",
        "value_number": 491.9,
        "unit": "",
        "sign_convention": "plain",
        "cell_bbox": None,
        "bbox_granularity": "table_only",
        "source_block_id": "p60_b2",
    }
    assert row["cells"][1]["value_raw"] == "△10.1"
    assert row["cells"][1]["value_number"] == -10.1
    assert row["cells"][1]["sign_convention"] == "negative_triangle"


def test_pdf_table_parser_extracts_currency_rows_from_header_and_row_blocks() -> None:
    records = extract_pdf_table_records(
        [
            block("p64_b0", "마. 주요국가의 환율변동 비교", [73.6, 76.45, 239.27, 88.44], 0),
            block("p64_b1", "한국(원/달러)\n일본(엔/달러)\n대만(NT달러/달러)\n유로(달러/EUR)", [80, 100, 450, 120], 1),
            block("p64_b2", "기말\n절상률\n기간평균\n기말\n절상률\n기말\n절상률\n기말\n절상률", [80, 125, 455, 145], 2),
            block(
                "p64_b3",
                "2018\n1,118.1\n△4.18\n1,100.30\n110.36\n2.29\n30.57\n△2.45\n1.1441\n△4.18",
                [80, 150, 455, 175],
                3,
            ),
        ],
        page_no=65,
        physical_page_index=64,
    )

    assert len(records) == 1
    table = records[0]
    assert table["table_type"] == "currency_comparison"
    assert table["title_block_id"] == "p64_b0"
    assert table["header_blocks"][0]["block_id"] == "p64_b1"
    row = table["row_records"][0]
    assert row["row_bbox"] == [80.0, 150.0, 455.0, 175.0]
    assert row["source_block_ids"] == ["p64_b3"]
    assert row["cells"][0]["column_path"] == "한국(원/달러) 기말"
    assert row["cells"][0]["value_raw"] == "1,118.1"
    assert row["cells"][-1]["column_path"] == "유로(달러/EUR) 절상률"
    assert row["cells"][-1]["value_raw"] == "△4.18"


def test_pdf_table_parser_does_not_emit_chart_title_or_ocr_fragment() -> None:
    records = extract_pdf_table_records(
        [
            block("p28_b0", "경상수지 추이", [240.83, 77.66, 313.57, 89.03], 0),
            block("p28_b1", "상품수지\n서비스수지\n경상수지\n(십억$)", [90, 130, 170, 200], 1),
            block("p28_b2", "20\n15\n10\n5\n0", [180, 100, 200, 200], 2),
            block("p0_ocr_0", "$32 }$", [100, 100, 140, 115], 3, block_type="ocr_line_group", ocr_used=True),
        ],
        page_no=29,
        physical_page_index=28,
    )

    assert records == []


def block(
    block_id: str,
    text: str,
    bbox: list[float],
    reading_order: int,
    *,
    block_type: str = "paragraph",
    ocr_used: bool = False,
) -> dict:
    return {
        "block_id": block_id,
        "block_type": block_type,
        "text": text,
        "bbox": bbox,
        "reading_order": reading_order,
        "section_path": [],
        "ocr_used": ocr_used,
    }
