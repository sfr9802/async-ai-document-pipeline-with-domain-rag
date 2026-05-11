from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from app.capabilities.rag.generation import RetrievedChunk
from app.capabilities.rag.search_unit_indexing import (
    build_search_unit_embedding_text,
    document_from_claim,
    to_chunk_row,
)
from app.capabilities.rag_orchestrator.evidence import QueryPolicy
from app.capabilities.rag_orchestrator.vector_tools import text_vector_search_tool


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPT = ROOT / "scripts" / "rag_phase2_review_unlock_estimator.py"
OFFICIAL_DENOMINATOR = ROOT / "eval" / "eval_queries" / "official_denominator_registry.json"
DIAGNOSTIC_NAMESPACE = "phase2b-diagnostic-smoke"
DIAGNOSTIC_PARSER_VERSION = "phase2b-diagnostic-parser-v1"


@dataclass(frozen=True)
class _DiagnosticReport:
    query: str
    top_k: int
    index_version: str
    embedding_model: str
    results: list[RetrievedChunk]


class _DiagnosticNamespaceRetriever:
    def __init__(self, rows: list[RetrievedChunk]) -> None:
        self._rows = rows
        self._top_k = 1
        self._candidate_k = 1
        self.calls: list[dict[str, Any]] = []
        self.production_vector_write = False
        self.production_namespace_mutation = False
        self.created_namespaces: list[str] = []

    def retrieve(self, query: str, filters=None) -> _DiagnosticReport:
        self.calls.append({"query": query, "filters": filters, "namespace": DIAGNOSTIC_NAMESPACE})
        return _DiagnosticReport(
            query=query,
            top_k=self._top_k,
            index_version=DIAGNOSTIC_NAMESPACE,
            embedding_model="diagnostic-hash-embedding",
            results=self._rows[: self._top_k],
        )


def test_phase2b_current_inputs_policy_gates_and_report_assertions(tmp_path: Path):
    module = _load_module()
    _skip_if_default_inputs_missing(module)

    payload = module.run_estimator(output_dir=tmp_path / "phase2b-out")
    report = module.render_estimate_md(payload)
    views = payload["derived_readiness_views"]
    priorities = {item["source_family_id"]: item for item in payload["source_family_priorities"]}

    official_rag = views["official_denominator_readiness"]["rag_retrieval_core"]
    official_visual = views["official_denominator_readiness"]["visual_shadow"]
    promotion_rag = views["promotion_scope_readiness"]["rag_retrieval_core"]
    promotion_visual = views["promotion_scope_readiness"]["visual_shadow"]

    assert official_rag["row_level"]["current_numerator"] == 304
    assert official_rag["row_level"]["current_denominator"] == 512
    assert official_rag["row_level"]["after_conservative_unlock_numerator"] == 390
    assert official_rag["canonical_level"]["current_numerator"] == 152
    assert official_rag["canonical_level"]["current_denominator"] == 252
    assert official_rag["canonical_level"]["after_conservative_unlock_numerator"] == 191

    assert official_visual["row_level"]["current_numerator"] == 144
    assert official_visual["row_level"]["current_denominator"] == 1244
    assert official_visual["row_level"]["after_conservative_unlock_numerator"] == 416
    assert official_visual["canonical_level"]["current_numerator"] == 72
    assert official_visual["canonical_level"]["current_denominator"] == 622
    assert official_visual["canonical_level"]["after_conservative_unlock_numerator"] == 208

    assert promotion_rag["row_level"]["current_numerator"] == 40
    assert promotion_rag["row_level"]["current_denominator"] == 40
    assert promotion_rag["row_level"]["current_rate"] == 1.0
    assert promotion_rag["canonical_level"]["current_numerator"] == 20
    assert promotion_rag["canonical_level"]["current_denominator"] == 20
    assert promotion_rag["canonical_level"]["current_rate"] == 1.0

    assert promotion_visual["row_level"]["current_numerator"] == 54
    assert promotion_visual["row_level"]["current_denominator"] == 56
    assert promotion_visual["canonical_level"]["current_numerator"] == 27
    assert promotion_visual["canonical_level"]["current_denominator"] == 28

    for item in priorities.values():
        if item["classification"] == "DIAGNOSTIC_ONLY":
            assert item["public_release_allowed_rows"] == 0
            assert item["support_eligible_rows"] == 0
            assert item["gold_candidate_allowed_rows"] == 0

    namu = priorities["NAMU"]
    assert namu["classification"] == "DIAGNOSTIC_ONLY"
    assert namu["policy_posture"] == "NONCOMMERCIAL_LIMITED"
    assert namu["license_statuses"] == "VERIFIED_NONCOMMERCIAL_ONLY"
    assert namu["public_release_allowed_rows"] == 0
    assert namu["support_eligible_rows"] == 0
    assert namu["gold_candidate_allowed_rows"] == 0

    funsd = priorities["FUNSD"]
    assert funsd["classification"] == "DIAGNOSTIC_ONLY"
    assert funsd["policy_posture"] == "OCR_MM_DIAGNOSTIC_ONLY"
    assert funsd["license_statuses"] == "VERIFIED_RESEARCH_ONLY"

    assert priorities["KOSIS"]["license_statuses"] == "VERIFIED_OPEN_PUBLIC_DATA"
    kosis_state = views["kosis_state"]
    assert kosis_state["vector_stage_eligible"] == {"rows": 2, "canonical_rows": 1}
    assert kosis_state["support_eligible"]["rows"] == 0
    assert kosis_state["gold_candidate_allowed"]["rows"] == 0
    assert kosis_state["license_evidence_level"] == "source_family_or_terms_page_only"

    assert priorities["PUBLIC_DATA_PORTAL"]["license_statuses"] == (
        "VERIFIED_KOGL_TYPE_1|VERIFIED_KOGL_TYPE_2_NONCOMMERCIAL|"
        "VERIFIED_KOGL_TYPE_4_NONCOMMERCIAL_NO_DERIVATIVES|VERIFIED_OPEN_PUBLIC_DATA"
    )
    assert priorities["SEOUL_OPEN_DATA"]["license_statuses"] == (
        "LICENSE_INFERRED_FROM_CATALOG_BUT_UNVERIFIED|VERIFIED_KOGL_TYPE_1"
    )
    assert priorities["DART"]["license_statuses"] == "SOURCE_TERMS_FOUND_BUT_AMBIGUOUS"
    assert priorities["PRISM"]["license_statuses"] == "SOURCE_LICENSE_NOT_FOUND"

    diagnostic_drag = {
        item["source_family_id"]: item
        for item in views["diagnostic_drag_breakdown"]["visual_shadow"]
    }
    assert diagnostic_drag["FUNSD"]["row_promotion_scope_denominator"] == 0
    assert diagnostic_drag["FUNSD"]["row_denominator_drag"] == 796

    warnings = views["vector_readiness_promotion_block_warnings"]
    assert any(
        warning["source_family_id"] == "NAMU"
        and warning["warning"] == "counted_in_vector_readiness_but_blocked_from_public_support_gold_promotion"
        for warning in warnings
    )

    guardrails = payload["guardrail_status"]
    assert guardrails["official_denominator_registry_changed"] is False
    assert guardrails["production_index_mutation"] is False
    assert guardrails["production_vector_write"] is False
    assert guardrails["namespace_created"] is False
    assert guardrails["support_eligible_ocr_mm_count"] == 0
    assert guardrails["annotation_answer_embedding_count"] == 0
    assert guardrails["hidden_xlsx_exposed"] is False
    assert guardrails["promotion_evidence"] is False

    assert "`304/512 = 0.59375`" in report
    assert "`390/512 = 0.761719`" in report
    assert "`40/40 = 1.0`" in report
    assert "VERIFIED_NONCOMMERCIAL_ONLY" in report
    assert "SOURCE_LICENSE_NOT_FOUND" in report
    assert "NAMU" in report
    assert "KOSIS" in report


def test_phase2b_generated_outputs_are_ignored_tmp_and_not_docs(tmp_path: Path):
    module = _load_module()
    _skip_if_default_inputs_missing(module)

    assert module.DEFAULT_OUTPUT_DIR == REPO_ROOT / ".tmp" / "phase2-review-unlock"
    assert module.DEFAULT_OUTPUT_DIR != module.DEFAULT_DOCS_DIR
    ignored = subprocess.run(
        [
            "git",
            "check-ignore",
            "-q",
            ".tmp/phase2-review-unlock/phase2_review_unlock_estimate.json",
        ],
        cwd=REPO_ROOT,
        check=False,
    )
    assert ignored.returncode == 0
    default_payload = module.run_estimator(output_dir=module.DEFAULT_OUTPUT_DIR)
    assert all(".tmp" in path and "phase2-review-unlock" in path for path in default_payload["outputs"].values())

    out_dir = tmp_path / ".tmp" / "phase2-review-unlock"
    payload = module.run_estimator(output_dir=out_dir)
    module.write_outputs(out_dir, payload)

    for filename in module.REPORT_OUTPUTS.values():
        assert (out_dir / filename).exists()
        assert not (module.DEFAULT_DOCS_DIR / filename).exists()


def test_official_denominator_registry_unchanged_by_phase2b_validation(tmp_path: Path):
    module = _load_module()
    _skip_if_default_inputs_missing(module)
    before = _sha256(OFFICIAL_DENOMINATOR)

    payload = module.run_estimator(output_dir=tmp_path / "phase2b-out")
    module.write_outputs(tmp_path / "phase2b-out", payload)

    assert _sha256(OFFICIAL_DENOMINATOR) == before
    assert payload["guardrail_status"]["official_denominator_registry_changed"] is False


def test_diagnostic_retrieval_smoke_preserves_policy_metadata_and_namespace_isolation():
    chunk = _diagnostic_retrieved_chunk()
    retriever = _DiagnosticNamespaceRetriever([chunk])
    policy = QueryPolicy(
        request_id="phase2b-diagnostic-smoke",
        required_index_version=DIAGNOSTIC_NAMESPACE,
        allowed_source_file_types=("TEXT",),
        allowed_parser_versions=(DIAGNOSTIC_PARSER_VERSION,),
        top_k=1,
    )

    result = text_vector_search_tool("diagnostic policy metadata smoke", policy, retriever=retriever)

    assert result.backend_identity["index_namespace_filter"] == DIAGNOSTIC_NAMESPACE
    assert result.backend_identity["production_filter_enforcement"] is False
    assert retriever.production_vector_write is False
    assert retriever.production_namespace_mutation is False
    assert retriever.created_namespaces == []
    assert len(result.evidence) == 1
    assert result.rejected == ()

    evidence = result.evidence[0]
    metadata = evidence.extra["retriever_metadata"]
    assert evidence.diagnostic_only is True
    assert evidence.to_dict()["diagnosticOnly"] is True
    assert metadata["source_family_id"] == "NAMU"
    assert metadata["license_status"] == "VERIFIED_NONCOMMERCIAL_ONLY"
    assert metadata["policy_posture"] == "NONCOMMERCIAL_LIMITED"
    assert metadata["canonical_row_id"] == "canon-phase2b-diagnostic-namu"
    assert metadata["lane"] == "TEXT_NAMU"
    assert metadata["public_release_allowed"] is False
    assert metadata["support_eligible"] is False
    assert metadata["gold_candidate_allowed"] is False
    assert metadata["vectorId"].startswith(f"{DIAGNOSTIC_NAMESPACE}:")


def _diagnostic_retrieved_chunk() -> RetrievedChunk:
    doc = document_from_claim(
        {
            "searchUnitId": "unit-phase2b-diagnostic-namu",
            "claimToken": "claim-phase2b-diagnostic",
            "indexId": "source_file:phase2b-diagnostic:unit:TEXT:section:license-policy",
            "sourceFileId": "phase2b-diagnostic",
            "sourceFileName": "phase2b_diagnostic_policy.txt",
            "extractedArtifactId": "artifact-phase2b-diagnostic",
            "artifactType": "TEXT",
            "unitType": "TEXT",
            "unitKey": "section:license-policy",
            "title": "Phase 2B diagnostic policy smoke",
            "sectionPath": "license-policy",
            "textContent": "Synthetic diagnostic smoke row for policy metadata validation.",
            "contentSha256": "phase2b-diagnostic-content-sha",
            "metadataJson": {"fileType": "text"},
            "indexMetadata": {
                "sourceFileType": "TEXT",
                "parserVersion": DIAGNOSTIC_PARSER_VERSION,
                "indexVersion": DIAGNOSTIC_NAMESPACE,
                "embeddingStatus": "EMBEDDED",
                "citationText": "phase2b_diagnostic_policy.txt license-policy",
                "locationJson": {"section_path": "license-policy", "char_start": 0, "char_end": 62},
                "locationType": "text_section",
                "chunkType": "diagnostic_smoke",
                "documentVersionId": "docver-phase2b-diagnostic",
                "diagnostic_only": True,
                "source_family_id": "NAMU",
                "license_status": "VERIFIED_NONCOMMERCIAL_ONLY",
                "policy_posture": "NONCOMMERCIAL_LIMITED",
                "public_release_allowed": False,
                "support_eligible": False,
                "gold_candidate_allowed": False,
                "canonical_row_id": "canon-phase2b-diagnostic-namu",
                "lane": "TEXT_NAMU",
            },
        }
    )
    embedding_text = build_search_unit_embedding_text(doc)
    chunk_row = to_chunk_row(
        doc,
        faiss_row_id=0,
        index_version=DIAGNOSTIC_NAMESPACE,
        embedding_model="diagnostic-hash-embedding",
        embedding_text=embedding_text,
    )
    extra = chunk_row.extra
    return RetrievedChunk(
        chunk_id=chunk_row.chunk_id,
        doc_id=chunk_row.doc_id,
        section=chunk_row.section,
        text=chunk_row.text,
        score=1.0,
        search_unit_id=extra["searchUnitId"],
        source_file_id=extra["sourceFileId"],
        source_file_name=extra["sourceFileName"],
        extracted_artifact_id=extra["extractedArtifactId"],
        artifact_type=extra["artifactType"],
        unit_type=extra["unitType"],
        unit_key=extra["unitKey"],
        metadata_json=extra,
    )


def _load_module():
    spec = importlib.util.spec_from_file_location("rag_phase2_review_unlock_estimator", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _skip_if_default_inputs_missing(module) -> None:
    required = [
        module.DEFAULT_ENRICHED_CSV,
        module.DEFAULT_REVIEW_REQUIRED_CSV,
        module.DEFAULT_REPORTS_DIR / "existing_manifest_experiment_readiness.md",
        module.DEFAULT_REPORTS_DIR / "existing_manifest_license_summary_by_source.md",
        module.DEFAULT_REPORTS_DIR / "existing_manifest_license_usage_gate.md",
        module.DEFAULT_DOCS_DIR / "phase1_visual_shadow_source_summary.csv",
        module.DEFAULT_DOCS_DIR / "phase1_review_license_status_summary.csv",
        module.DEFAULT_DOCS_DIR / "phase1_retrieval_core_source_summary.csv",
        module.DEFAULT_DOCS_DIR / "phase1_lane_readiness_summary.csv",
        module.DEFAULT_DOCS_DIR / "phase1_source_family_readiness_summary.csv",
        module.DEFAULT_DOCS_DIR / "phase1_csv_reanalysis.md",
        OFFICIAL_DENOMINATOR,
    ]
    missing = [path for path in required if not Path(path).exists()]
    if missing:
        pytest.skip(f"Phase 2B default input artifacts are not present: {missing[0]}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
