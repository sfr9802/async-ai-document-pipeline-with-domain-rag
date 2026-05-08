"""Diagnostic shadow-lane contracts for OCR, IDP, and multimodal evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


NATIVE_TEXT_HIGH = "NATIVE_TEXT_HIGH"
STRUCTURED_XLSX_HIGH = "STRUCTURED_XLSX_HIGH"
OCR_MEDIUM = "OCR_MEDIUM"
IDP_TABLE_MEDIUM = "IDP_TABLE_MEDIUM"
MULTIMODAL_CAPTION_LOW = "MULTIMODAL_CAPTION_LOW"
DIAGNOSTIC_ONLY = "DIAGNOSTIC_ONLY"

SHADOW_TRUST_TIERS = {OCR_MEDIUM, IDP_TABLE_MEDIUM, MULTIMODAL_CAPTION_LOW, DIAGNOSTIC_ONLY}
TRUST_RANK = {
    NATIVE_TEXT_HIGH: 100,
    STRUCTURED_XLSX_HIGH: 95,
    OCR_MEDIUM: 60,
    IDP_TABLE_MEDIUM: 55,
    MULTIMODAL_CAPTION_LOW: 25,
    DIAGNOSTIC_ONLY: 0,
}

CONTRACT_FIELDS = (
    "parser_version",
    "location_json",
    "citation_text",
    "embedding_text",
    "bm25_text",
    "display_text",
    "debug_text",
)


@dataclass(frozen=True)
class ExtractionUnit:
    """Report-only OCR/IDP/multimodal extraction unit.

    The object can be converted into a diagnostic SearchUnit-shaped payload,
    but is not official-denominator eligible unless a later explicit policy
    marks it so.
    """

    unit_id: str
    lane: str
    trust_tier: str
    parser_version: str
    location_json: Mapping[str, Any]
    citation_text: str
    embedding_text: str
    bm25_text: str
    display_text: str
    debug_text: str
    confidence: float | None = None
    source_file_id: str | None = None
    source_file_name: str | None = None
    unit_type: str = "DIAGNOSTIC_EXTRACTION"
    official_denominator_eligible: bool = False
    denominator_role: str = DIAGNOSTIC_ONLY
    evidence_role: str = "diagnostic"
    extra: Mapping[str, Any] = field(default_factory=dict)

    def validate_contract(self) -> None:
        missing = [name for name in CONTRACT_FIELDS if not getattr(self, name)]
        if missing:
            raise ValueError("ExtractionUnit missing contract fields: " + ", ".join(missing))
        if self.trust_tier not in TRUST_RANK:
            raise ValueError(f"unknown trust_tier: {self.trust_tier}")
        if self.trust_tier in SHADOW_TRUST_TIERS and self.official_denominator_eligible:
            raise ValueError("shadow trust tiers are diagnostic-only by default")


def to_diagnostic_search_unit(unit: ExtractionUnit) -> dict[str, Any]:
    unit.validate_contract()
    payload = asdict(unit)
    payload.update(
        {
            "search_unit_id": unit.unit_id,
            "unitType": unit.unit_type,
            "evidence_role": "diagnostic",
            "denominator_role": DIAGNOSTIC_ONLY,
            "official_denominator_eligible": False,
            "trust_tier": unit.trust_tier,
        }
    )
    return payload


def assert_can_enter_official_denominator(unit: ExtractionUnit, *, explicit_policy: bool = False) -> None:
    unit.validate_contract()
    if unit.trust_tier in SHADOW_TRUST_TIERS and not explicit_policy:
        raise ValueError(f"{unit.trust_tier} cannot enter official denominators without explicit policy")
    if unit.denominator_role == DIAGNOSTIC_ONLY and not explicit_policy:
        raise ValueError("diagnostic-only ExtractionUnit cannot enter official denominators")


def trust_sort_key(unit: ExtractionUnit) -> tuple[int, float]:
    confidence = unit.confidence if unit.confidence is not None else 0.0
    return (TRUST_RANK[unit.trust_tier], confidence)


def rank_by_trust(units: list[ExtractionUnit]) -> list[ExtractionUnit]:
    for unit in units:
        unit.validate_contract()
    return sorted(units, key=trust_sort_key, reverse=True)
