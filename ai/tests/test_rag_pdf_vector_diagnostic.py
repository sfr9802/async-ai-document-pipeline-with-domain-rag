from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "ai" / "scripts" / "rag_pdf_vector_diagnostic.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rag_pdf_vector_diagnostic", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


c5_module = load_module()


REQUIRED_COLUMNS = [
    "query_id",
    "bucket",
    "query",
    "expected_file_name",
    "expected_document_version_id",
    "expected_chunk_type",
    "expected_location_type",
    "expected_sheet_name",
    "expected_cell_range",
    "expected_table_id",
    "expected_physical_page_index",
    "expected_page_no",
    "expected_page_label",
    "expected_bbox",
    "expected_answer_text",
    "must_contain_terms",
    "must_not_contain_terms",
    "range_match_policy",
    "hidden_policy",
    "requires_formula_value",
    "requires_formatted_value",
    "requires_aggregation",
    "source_sample_id",
    "label_status",
    "notes",
]


def test_c5_runs_pdf_only_diagnostic_with_carry_forward_warnings(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    args = base_args(paths)
    payload = c5_module.build_report(args, search_fn_override=matching_search)

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["phase"] == "C5"
    assert payload["retrieval_backend"] == "vector"
    assert payload["promotion_evidence"] is False
    assert payload["evidence_role"] == "diagnostic"
    assert payload["namespace"] == c5_module.PDF_INDEX_VERSION
    assert payload["artifact_dir"] == "ai/eval/indexes/rag-data-pdf-candidate-v1"
    assert payload["gold_filter"]["selected_pdf_positive_row_count"] == 1
    assert payload["query_level_results_available"] is True
    assert payload["pdf_metrics"]["pdf_file_hit@10"] == 1.0
    assert payload["pdf_metrics"]["pdf_page_hit@10"] == 1.0
    assert payload["pdf_metrics"]["pdf_bbox_overlap@10"] == 1.0
    assert payload["metadata_projection_failure_count"] == 0
    assert payload["true_retrieval_ranking_failure_count"] == 0
    assert payload["vector_contract_counters"]["top_k_non_pdf_hit_count"] == 0
    assert payload["vector_contract_counters"]["top_k_missing_source_file_type_count"] == 0
    assert payload["candidate_namespace_chunk_count"] == 8194
    assert payload["scope_leakage_detected"] is False
    assert payload["non_pdf_row_count"] == 0
    assert payload["policy_excluded_leakage_count"] == 0
    assert payload["immutable_baseline_changed"] is False
    assert payload["xlsx_candidate_artifact_changed"] is False
    assert payload["c6_ready"] is True
    assert payload["warnings_carried_forward"] == list(c5_module.PDF_ONLY_WARNING_KEYS)


def test_c5_separates_ranking_failure_without_gold_policy_prompt(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    args = base_args(paths)
    payload = c5_module.build_report(args, search_fn_override=wrong_page_search)

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["metadata_projection_failure_count"] == 0
    assert payload["true_retrieval_ranking_failure_count"] == 1
    assert payload["diagnostic_failure_classification"]["failure_reason_counts"] == {
        "expected_page_not_found": 1
    }
    assert payload["c7_policy_review_required_now"] is False
    assert not payload["blockers"]


def test_c5_counts_unknown_as_unclassified_retrieval_failure(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    args = base_args(paths)
    payload = c5_module.build_report(args, search_fn_override=chunk_type_mismatch_search)

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["diagnostic_failure_classification"]["failure_reason_counts"] == {"unknown": 1}
    assert payload["diagnostic_failure_classification"]["unclassified_failure_count"] == 1
    assert payload["true_retrieval_ranking_failure_count"] == 1
    assert not payload["blockers"]


def test_c5_allows_separated_metadata_projection_failures_for_c6(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    args = base_args(paths)
    payload = c5_module.build_report(args, search_fn_override=page_hit_missing_bbox_search)

    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert payload["metadata_projection_failure_count"] == 1
    assert "C5 separated metadata projection failures for C6; not a C5 blocker." in payload["warnings"]
    assert not payload["blockers"]
    assert payload["c6_ready"] is True


def test_c5_fails_when_c4_scope_leakage_is_present(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    c4 = c4_report()
    c4["non_pdf_row_count"] = 1
    write_json(paths["c4"], c4)

    payload = c5_module.build_report(base_args(paths), search_fn_override=matching_search)

    assert payload["status"] == "FAIL"
    assert "C4 non_pdf_row_count must be 0 before C5" in payload["blockers"]
    assert payload["retrieval_execution"] == "not_run"
    assert payload["c6_ready"] is False


def test_c5_fails_closed_on_vector_search_errors(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)

    payload = c5_module.build_report(base_args(paths), search_fn_override=failing_search)

    assert payload["status"] == "FAIL"
    assert payload["diagnostic_failure_classification"]["search_error_count"] == 1
    assert "search_error_count must be 0" in payload["blockers"]
    assert payload["query_level_results_available"] is True
    assert payload["c6_ready"] is False


def test_c5_filters_only_bound_pdf_positive_rows(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    rows = [
        gold_row("pdf-ok", query="match me"),
        gold_row("pdf-pending", query="pending", label_status="pending"),
        gold_row("pdf-negative", query="negative", hidden_policy="negative"),
        gold_row("xlsx-row", query="xlsx", bucket="xlsx_lookup", expected_location_type="xlsx"),
    ]
    write_gold(paths["gold"], rows)

    payload = c5_module.build_report(base_args(paths), search_fn_override=matching_search)

    assert payload["gold_filter"]["selected_pdf_positive_row_count"] == 1
    assert payload["gold_filter"]["excluded_counts"] == {
        "hidden_policy_negative": 1,
        "label_status_pending": 1,
        "non_pdf": 1,
    }
    assert payload["validation"]["ok"] is True


def test_c5_infers_pdf_source_type_from_location_when_vector_hit_omits_raw_type(tmp_path: Path, monkeypatch):
    paths = fixture_paths(tmp_path, monkeypatch)
    payload = c5_module.build_report(base_args(paths), search_fn_override=missing_raw_source_type_search)

    counters = payload["vector_contract_counters"]
    first_hit = payload["query_results"][0]["top_k_results"][0]
    assert payload["status"] == "PASS_WITH_WARNINGS"
    assert counters["top_k_raw_source_file_type_missing_count"] == 1
    assert counters["top_k_source_file_type_inferred_count"] == 1
    assert counters["top_k_missing_source_file_type_count"] == 0
    assert counters["top_k_non_pdf_hit_count"] == 0
    assert first_hit["source_file_type"] == "PDF"
    assert first_hit["source_file_type_inferred"] is True
    assert not payload["blockers"]


def fixture_paths(tmp_path: Path, monkeypatch) -> dict[str, Path]:
    root = tmp_path
    ai_worker = root / "ai"
    monkeypatch.setattr(c5_module, "ROOT", root)
    monkeypatch.setattr(c5_module, "AI_WORKER", ai_worker)
    reports = ai_worker / "eval" / "reports" / "rag-ingestion"
    reports.mkdir(parents=True)
    gold = ai_worker / "eval" / "eval_queries" / "gold_queries_pdf_v0.csv"
    artifact = ai_worker / "eval" / "indexes" / "rag-data-pdf-candidate-v1"
    artifact.mkdir(parents=True)
    (artifact / "faiss.index").write_text("index", encoding="utf-8")
    (artifact / "ingest_manifest.json").write_text("{}", encoding="utf-8")
    (artifact / "build.json").write_text(
        json.dumps({
            "index_version": c5_module.PDF_INDEX_VERSION,
            "embedding_model": "BAAI/bge-m3",
            "dimension": 1024,
            "chunk_count": 8194,
        }),
        encoding="utf-8",
    )
    paths = {
        "gold": gold,
        "c1": reports / "pdf_candidate_scope_report.json",
        "c2": reports / "pdf_vector_metadata_projection_readiness.json",
        "c3": reports / "rag_pdf_embedding_text_contract_audit.json",
        "c4": reports / "pdf_candidate_embedding_consistency_report.json",
        "report": reports / "rag_retrieval_eval_pdf_vector_diagnostic_report.json",
        "artifact": artifact,
    }
    write_gold(gold, [gold_row("pdf-ok", query="match me")])
    write_json(paths["c1"], c1_report())
    write_json(paths["c2"], c2_report())
    write_json(paths["c3"], c3_report())
    write_json(paths["c4"], c4_report())
    return paths


def base_args(paths: dict[str, Path]):
    return c5_module.parse_args([
        "--gold",
        str(paths["gold"]),
        "--c1-report",
        str(paths["c1"]),
        "--c2-report",
        str(paths["c2"]),
        "--c3-report",
        str(paths["c3"]),
        "--c4-report",
        str(paths["c4"]),
        "--artifact-dir",
        str(paths["artifact"]),
        "--report",
        str(paths["report"]),
        "--expected-location-type",
        "pdf",
    ])


def matching_search(query: str, top_k: int):
    return [pdf_hit(page_no=1, physical_page_index=0, bbox=[0, 0, 10, 10])]


def wrong_page_search(query: str, top_k: int):
    return [pdf_hit(page_no=2, physical_page_index=1, bbox=[0, 0, 10, 10])]


def chunk_type_mismatch_search(query: str, top_k: int):
    return [pdf_hit(page_no=1, physical_page_index=0, bbox=[0, 0, 10, 10], chunk_type="page")]


def page_hit_missing_bbox_search(query: str, top_k: int):
    return [pdf_hit(page_no=1, physical_page_index=0, bbox=[])]


def missing_raw_source_type_search(query: str, top_k: int):
    return [pdf_hit(page_no=1, physical_page_index=0, bbox=[0, 0, 10, 10], include_source_type=False)]


def failing_search(query: str, top_k: int):
    raise RuntimeError("metadata store unavailable")


def pdf_hit(
    *,
    page_no: int,
    physical_page_index: int,
    bbox: list[int],
    chunk_type: str = "paragraph",
    include_source_type: bool = True,
):
    location = {
        "type": "pdf",
        "page_no": page_no,
        "physical_page_index": physical_page_index,
        "document_version_id": "docv_pdf",
        "index_version": c5_module.PDF_INDEX_VERSION,
    }
    if bbox:
        location["bbox"] = bbox
    return {
        "sourceFile": {
            "originalFileName": "sample.pdf",
            **({"fileType": "PDF"} if include_source_type else {}),
        },
        "searchUnit": {
            "id": "su_pdf",
            "chunkType": chunk_type,
            "locationType": "pdf",
            **({"sourceFileType": "PDF"} if include_source_type else {}),
            "citationText": "p.1",
            "embeddingStatus": "EMBEDDED",
            "indexVersion": c5_module.PDF_INDEX_VERSION,
            "documentVersionId": "docv_pdf",
            "locationJson": location,
        },
        "score": 0.9,
    }


def gold_row(
    query_id: str,
    *,
    query: str,
    bucket: str = "pdf_page_lookup",
    expected_location_type: str = "pdf",
    label_status: str = "bound",
    hidden_policy: str = "",
) -> dict[str, str]:
    row = {key: "" for key in REQUIRED_COLUMNS}
    row.update({
        "query_id": query_id,
        "bucket": bucket,
        "query": query,
        "expected_file_name": "sample.pdf",
        "expected_document_version_id": "docv_pdf",
        "expected_chunk_type": "paragraph",
        "expected_location_type": expected_location_type,
        "expected_physical_page_index": "0",
        "expected_page_no": "1",
        "expected_bbox": "[0, 0, 10, 10]",
        "range_match_policy": "none",
        "hidden_policy": hidden_policy,
        "requires_formula_value": "false",
        "requires_formatted_value": "false",
        "requires_aggregation": "false",
        "label_status": label_status,
    })
    if expected_location_type == "xlsx":
        row.update({
            "expected_file_name": "book.xlsx",
            "expected_sheet_name": "Sheet1",
            "expected_cell_range": "A1:A1",
            "expected_physical_page_index": "",
            "expected_page_no": "",
            "expected_bbox": "",
        })
    return row


def c1_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "allowUnscoped": False,
    }


def c2_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "summary": {
            "policy_excluded_ocr_confidence_missing_count": 6,
            "policy_excluded_document_summary_count": 3,
        },
    }


def c3_report() -> dict:
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "summary": {
            "skipped_searchable_row_count": 9,
        },
        "table_contract": {
            "pdf_table_gold_count": 6,
            "table_like_search_unit_count": 0,
        },
    }


def c4_report() -> dict:
    zero_fields = {
        "unexpected_sourceFileId_count": 0,
        "unexpected_documentVersionId_count": 0,
        "non_pdf_row_count": 0,
        "policy_excluded_leakage_count": 0,
        "missing_location_json_locationJson_count": 0,
        "jackson_jsonnode_shape_location_count": 0,
        "unusable_location_count": 0,
        "missing_physical_page_index_count": 0,
        "missing_page_no_count": 0,
        "missing_bbox_count": 0,
        "missing_citation_text_count": 0,
        "missing_embedding_text_count": 0,
        "missing_source_page_citation_block_surface_count": 0,
        "ocr_trust_marker_missing_count": 0,
    }
    return {
        "status": "PASS_WITH_WARNINGS",
        "promotion_evidence": False,
        "evidence_role": "diagnostic",
        "allowUnscoped": False,
        "namespace": c5_module.PDF_INDEX_VERSION,
        "artifact_dir": "ai/eval/indexes/rag-data-pdf-candidate-v1",
        "scoped_search_unit_count": 8203,
        "indexable_search_unit_count": 8194,
        "policy_excluded_search_unit_count": 9,
        "candidate_namespace_chunk_count": 8194,
        "candidate_chunk_count_matches_indexable_rows": True,
        "immutable_baseline_changed": False,
        "xlsx_candidate_artifact_changed": False,
        "c5_ready": True,
        "scope": {
            "document_version_ids": ["docv_pdf"],
            "source_file_ids": ["sf_pdf"],
            "parser_versions": ["pdf-extract-v1", "pdf-extract-v2"],
        },
        "warnings_carried_forward": list(c5_module.PDF_ONLY_WARNING_KEYS),
        **zero_fields,
    }


def write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_gold(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
