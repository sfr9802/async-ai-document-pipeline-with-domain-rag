from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "rag_pdf_reviewed_vector_diagnostic.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


diag_module = load_module("rag_pdf_reviewed_vector_diagnostic", MODULE_PATH)


def test_reviewed_diagnostic_excludes_deferred_tables_and_counts_policy_success(tmp_path: Path):
    artifact = tmp_path / "rag-data-pdf-candidate-v1"
    write_artifact(artifact)

    payload = diag_module.build_reviewed_diagnostic(
        reviewed_manifest_rows=manifest_rows(),
        policy_overlay=policy_overlay(),
        source_eval_report=source_eval_report(),
        reviewed_manifest_path=Path("reviewed.csv"),
        policy_overlay_path=Path("overlay.json"),
        source_eval_report_path=Path("c5.json"),
        artifact_dir=artifact,
    )

    metrics = payload["metrics"]
    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert metrics["reviewed_query_count"] == 5
    assert metrics["reviewed_positive_metric_denominator"] == 4
    assert metrics["deferred_table_count"] == 1
    assert metrics["Hit@1"] == 0.5
    assert metrics["Hit@5"] == 0.75
    assert metrics["pdf_policy_adjusted_location_accuracy"] == 0.75
    assert metrics["true_retrieval_ranking_failure_count"] == 1
    assert metrics["table_specific_success_count"] == 0
    assert payload["table_specific_retrieval_proven"] is False
    page_optional = next(row for row in payload["rows"] if row["query_id"] == "q-bbox")
    assert page_optional["page_with_optional_bbox_success"] is True
    assert page_optional["pdf_exact_bbox_at_10"] is False


def test_reviewed_diagnostic_blocks_promotion_evidence(tmp_path: Path):
    artifact = tmp_path / "rag-data-pdf-candidate-v1"
    write_artifact(artifact)
    source = source_eval_report()
    source["promotion_evidence"] = True

    payload = diag_module.build_reviewed_diagnostic(
        reviewed_manifest_rows=manifest_rows(),
        policy_overlay=policy_overlay(),
        source_eval_report=source,
        reviewed_manifest_path=Path("reviewed.csv"),
        policy_overlay_path=Path("overlay.json"),
        source_eval_report_path=Path("c5.json"),
        artifact_dir=artifact,
    )

    assert payload["status"] == "FAIL"
    assert "source C5 eval report must keep promotion_evidence=false" in payload["blockers"]


def test_reviewed_diagnostic_blocks_failed_policy_overlay(tmp_path: Path):
    artifact = tmp_path / "rag-data-pdf-candidate-v1"
    write_artifact(artifact)
    overlay = policy_overlay()
    overlay["status"] = "FAIL"

    payload = diag_module.build_reviewed_diagnostic(
        reviewed_manifest_rows=manifest_rows(),
        policy_overlay=overlay,
        source_eval_report=source_eval_report(),
        reviewed_manifest_path=Path("reviewed.csv"),
        policy_overlay_path=Path("overlay.json"),
        source_eval_report_path=Path("c5.json"),
        artifact_dir=artifact,
    )

    assert payload["status"] == "FAIL"
    assert "policy overlay must be PASS or PASS_WITH_WARNINGS; got FAIL" in payload["blockers"]


def test_reviewed_diagnostic_blocks_incomplete_artifact_contract(tmp_path: Path):
    artifact = tmp_path / "rag-data-pdf-candidate-v1"
    artifact.mkdir()

    payload = diag_module.build_reviewed_diagnostic(
        reviewed_manifest_rows=manifest_rows(),
        policy_overlay=policy_overlay(),
        source_eval_report=source_eval_report(),
        reviewed_manifest_path=Path("reviewed.csv"),
        policy_overlay_path=Path("overlay.json"),
        source_eval_report_path=Path("c5.json"),
        artifact_dir=artifact,
    )

    assert payload["status"] == "FAIL"
    assert "PDF candidate artifact build.json is missing" in payload["blockers"]
    assert "PDF candidate artifact ingest_manifest.json is missing" in payload["blockers"]
    assert "PDF candidate artifact faiss.index is missing" in payload["blockers"]


def write_artifact(path: Path) -> None:
    path.mkdir()
    index_version = "rag-ingestion-v2-pdf-candidate-v1"
    (path / "build.json").write_text(f'{{"index_version":"{index_version}"}}', encoding="utf-8")
    (path / "ingest_manifest.json").write_text(f'{{"index_version":"{index_version}"}}', encoding="utf-8")
    (path / "faiss.index").write_bytes(b"fake-faiss-index")


def manifest_rows() -> list[dict[str, str]]:
    return [
        manifest("q-match", "KEEP_REVIEWED_POSITIVE", "EXACT_PAGE_AND_BBOX", "positive_reviewed", "true"),
        manifest("q-bbox", "ACCEPT_PAGE_WITH_OPTIONAL_BBOX", "PAGE_WITH_OPTIONAL_BBOX", "positive_reviewed", "true"),
        manifest("q-chunk", "ACCEPT_CHUNK_TYPE_POLICY_RELABEL", "PAGE_OR_PARAGRAPH_SAME_PAGE", "positive_reviewed", "true", bbox=""),
        manifest("q-fail", "KEEP_REVIEWED_POSITIVE", "EXACT_PAGE_AND_BBOX", "positive_reviewed", "true"),
        manifest("q-table", "DEFER_TO_TABLE_EXTRACTION", "TABLE_EXTRACTION_REQUIRED", "table_deferred", "false"),
    ]


def source_eval_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "retrieval_backend": "vector",
        "index_version": "rag-ingestion-v2-pdf-candidate-v1",
        "metadata_projection_failure_count": 0,
        "metrics": {"Hit@10": 0.8},
        "query_results": [
            result("q-match", True, 1, None, [hit(1, page=1, exact=True, location=True)]),
            result("q-bbox", False, None, "bbox_mismatch", [
                hit(1, page=9),
                hit(4, page=1, chunk_type="page", bbox=False, location=False),
            ]),
            result("q-chunk", False, None, "unknown", [
                hit(1, page=1, chunk_type="paragraph", chunk_type_match=False, location=True, bbox=True),
            ]),
            result("q-fail", False, None, "expected_page_not_found", [hit(1, page=99)]),
            result("q-table", False, None, "expected_page_not_found", [hit(1, page=2)]),
        ],
    }


def policy_overlay() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "unresolved_candidate_count": 0,
    }


def manifest(
    query_id: str,
    decision: str,
    policy: str,
    review_label: str,
    eligible: str,
    *,
    bbox: str = "[1, 2, 3, 4]",
) -> dict[str, str]:
    return {
        "query_id": query_id,
        "bucket": "pdf_page_lookup",
        "query": "query",
        "expected_file_name": "sample.pdf",
        "expected_document_version_id": "docv",
        "expected_chunk_type": "paragraph",
        "expected_location_type": "pdf",
        "expected_physical_page_index": "0",
        "expected_page_no": "1",
        "expected_page_label": "1",
        "expected_bbox": bbox,
        "review_decision": decision,
        "pdf_match_policy": policy,
        "pdf_review_label": review_label,
        "positive_metric_eligible": eligible,
    }


def result(query_id: str, location_match: bool, location_rank: int | None, failure: str | None, hits: list[dict]) -> dict:
    return {
        "query_id": query_id,
        "bucket": "pdf_page_lookup",
        "query": "query",
        "hit_rank": 1 if hits else None,
        "location_rank": location_rank,
        "location_match": location_match,
        "failure_reason": failure,
        "top_k_results": hits,
    }


def hit(
    rank: int,
    *,
    page: int,
    chunk_type: str = "paragraph",
    chunk_type_match: bool = True,
    bbox: bool = True,
    exact: bool = False,
    location: bool = False,
) -> dict:
    return {
        "rank": rank,
        "score": 1.0 / rank,
        "search_unit_id": f"su-{rank}",
        "source_file_name": "sample.pdf",
        "chunk_type": chunk_type,
        "citation_text": f"sample.pdf > p.{page}",
        "location_json": {
            "type": "pdf",
            "document_version_id": "docv",
            "page_no": page,
            "physical_page_index": page - 1,
            "page_label": str(page),
            **({"bbox": [1, 2, 3, 4]} if bbox else {}),
        },
        "match_breakdown": {
            "file_match": True,
            "document_version_match": True,
            "chunk_type_match": chunk_type_match,
            "pdf_page_match": page == 1,
            "pdf_bbox_overlap": bbox and page == 1,
            "pdf_exact_bbox": exact,
            "location_match": location,
        },
    }
