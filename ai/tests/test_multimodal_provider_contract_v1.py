from __future__ import annotations

import base64
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))


def test_vision_provider_result_schema_carries_evidence_regions_without_answer_truth() -> None:
    from app.capabilities.multimodal.vision_provider import (
        VisionDescriptionResult,
        VisionEvidenceRegion,
    )

    region = VisionEvidenceRegion(
        region_id="page-1-image",
        page_id="1",
        bbox=[0.0, 0.0, 10.0, 20.0],
        block_type="image",
        confidence=0.72,
        ocr_source="provider_layout",
        provider_version="provider-v1",
        evidence_source_ids=("source-atom-1",),
    )
    result = VisionDescriptionResult(
        provider_name="provider-v1",
        caption="bounded description",
        evidence_regions=[region],
    )

    assert result.evidence_regions == [region]
    assert result.provider_role == "evidence_structure_provider"
    assert not hasattr(result, "answer")
    assert result.evidence_regions[0].block_type in {"image", "table", "text"}
    assert result.evidence_regions[0].evidence_source_ids == ("source-atom-1",)


def test_heuristic_vision_provider_emits_ci_fallback_region_schema() -> None:
    from app.capabilities.multimodal.heuristic_vision import HeuristicVisionProvider

    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )

    result = HeuristicVisionProvider().describe_image(
        png_1x1,
        mime_type="image/png",
        hint="테스트 이미지",
        page_number=3,
    )

    assert result.provider_name == "heuristic-vision-v1"
    assert result.provider_role == "ci_offline_fallback"
    assert result.evidence_regions
    region = result.evidence_regions[0]
    assert region.region_id == "heuristic-page-3-image"
    assert region.page_id == "3"
    assert region.bbox == [0.0, 0.0, 1.0, 1.0]
    assert region.block_type == "image"
    assert region.confidence == 0.0
    assert region.ocr_source == "heuristic_offline_fallback"
    assert region.provider_version == result.provider_name
    assert region.evidence_source_ids == ()


def test_vision_result_artifact_json_is_versioned_and_evidence_only() -> None:
    import json

    from app.capabilities.multimodal.capability import MultimodalCapability
    from app.capabilities.multimodal.vision_provider import (
        VisionDescriptionResult,
        VisionEvidenceRegion,
    )

    result = VisionDescriptionResult(
        provider_name="provider-v1",
        provider_role="evidence_structure_provider",
        caption="bounded description",
        evidence_regions=[
            VisionEvidenceRegion(
                region_id="page-1-text",
                page_id="1",
                bbox=[1.0, 2.0, 3.0, 4.0],
                block_type="text",
                confidence=0.44,
                ocr_source="provider_layout",
                provider_version="provider-v1",
                evidence_source_ids=("source-atom-1",),
            )
        ],
    )

    payload = json.loads(
        MultimodalCapability._vision_result_json(
            vision_pages=[result],
            filename="sample.png",
            mime_type="image/png",
            kind="image",
            warnings=[],
        )
    )

    assert payload["schemaVersion"] == "multimodal_vision_result_v1"
    assert payload["answerQualityComputed"] is False
    page = payload["pages"][0]
    region = page["evidenceRegions"][0]
    assert page["providerRole"] == "evidence_structure_provider"
    assert region["bbox"] == [1.0, 2.0, 3.0, 4.0]
    assert 0.0 <= region["confidence"] <= 1.0
    assert region["evidenceSourceIds"] == ["source-atom-1"]
    forbidden_answer_fields = {"answer", "finalAnswer", "expectedAnswer", "supportingEvidence"}
    assert not forbidden_answer_fields & set(payload)
    assert not forbidden_answer_fields & set(page)
    assert not forbidden_answer_fields & set(region)
