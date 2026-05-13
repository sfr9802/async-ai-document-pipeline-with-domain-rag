from __future__ import annotations

import sys
from pathlib import Path

import pytest

AI_WORKER = Path(__file__).resolve().parents[1]
if str(AI_WORKER) not in sys.path:
    sys.path.insert(0, str(AI_WORKER))

from app.capabilities.rag.shadow_lane_contract import (
    IDP_TABLE_MEDIUM,
    MULTIMODAL_CAPTION_LOW,
    NATIVE_TEXT_HIGH,
    OCR_MEDIUM,
    ExtractionUnit,
    assert_can_enter_official_denominator,
    rank_by_trust,
    to_diagnostic_search_unit,
)


def test_ocr_idp_and_multimodal_units_are_diagnostic_only_by_default():
    for unit in [
        _unit("ocr-1", "OCR_SHADOW", OCR_MEDIUM),
        _unit("idp-1", "IDP_SHADOW", IDP_TABLE_MEDIUM),
        _unit("cap-1", "MULTIMODAL_SHADOW", MULTIMODAL_CAPTION_LOW),
    ]:
        payload = to_diagnostic_search_unit(unit)

        assert payload["official_denominator_eligible"] is False
        assert payload["denominator_role"] == "DIAGNOSTIC_ONLY"
        assert payload["evidence_role"] == "diagnostic"
        with pytest.raises(ValueError, match="cannot enter official denominators"):
            assert_can_enter_official_denominator(unit)


def test_native_pdf_text_outranks_ocr_fallback_when_both_exist():
    native = _unit("native-1", "PDF_CONTENT", NATIVE_TEXT_HIGH, confidence=0.70)
    ocr = _unit("ocr-1", "OCR_SHADOW", OCR_MEDIUM, confidence=0.99)

    assert rank_by_trust([ocr, native])[0] == native


def test_multimodal_caption_preserves_contract_fields_but_stays_diagnostic():
    unit = _unit("cap-1", "MULTIMODAL_SHADOW", MULTIMODAL_CAPTION_LOW)
    payload = to_diagnostic_search_unit(unit)

    for field in [
        "parser_version",
        "location_json",
        "citation_text",
        "embedding_text",
        "bm25_text",
        "display_text",
        "debug_text",
    ]:
        assert payload[field]
    assert payload["trust_tier"] == MULTIMODAL_CAPTION_LOW
    assert payload["denominator_role"] == "DIAGNOSTIC_ONLY"
    assert payload["official_denominator_eligible"] is False


def test_idp_key_value_and_table_units_cannot_enter_official_denominator_by_default():
    units = [
        _unit("idp-kv-1", "IDP_SHADOW", IDP_TABLE_MEDIUM, unit_type="IDP_KEY_VALUE_DIAGNOSTIC"),
        _unit("idp-table-1", "IDP_SHADOW", IDP_TABLE_MEDIUM, unit_type="IDP_TABLE_DIAGNOSTIC"),
    ]

    for unit in units:
        payload = to_diagnostic_search_unit(unit)

        assert payload["unitType"] in {"IDP_KEY_VALUE_DIAGNOSTIC", "IDP_TABLE_DIAGNOSTIC"}
        assert payload["denominator_role"] == "DIAGNOSTIC_ONLY"
        assert payload["official_denominator_eligible"] is False
        with pytest.raises(ValueError, match="cannot enter official denominators"):
            assert_can_enter_official_denominator(unit)


def _unit(
    unit_id: str,
    lane: str,
    trust_tier: str,
    *,
    confidence: float = 0.5,
    unit_type: str = "DIAGNOSTIC_EXTRACTION",
) -> ExtractionUnit:
    return ExtractionUnit(
        unit_id=unit_id,
        lane=lane,
        trust_tier=trust_tier,
        parser_version="shadow-contract-v1",
        location_json={"type": lane.lower(), "page": 1},
        citation_text=f"{lane} diagnostic citation",
        embedding_text=f"{lane} embedding text",
        bm25_text=f"{lane} bm25 text",
        display_text=f"{lane} display text",
        debug_text=f"{lane} debug text",
        confidence=confidence,
        unit_type=unit_type,
    )
